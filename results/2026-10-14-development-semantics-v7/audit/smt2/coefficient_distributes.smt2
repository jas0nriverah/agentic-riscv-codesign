(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun a () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x31 (bvmul a x)))
(let ((?x41 (bvadd ?x31 (bvmul a y))))
(let ((?x19 (bvadd x y)))
(let ((?x39 (bvmul a ?x19)))
(and (distinct ?x39 ?x41) true))))))
(check-sat)
