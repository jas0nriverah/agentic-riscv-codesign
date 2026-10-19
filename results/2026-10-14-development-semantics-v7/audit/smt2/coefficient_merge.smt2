(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(declare-fun b () (_ BitVec 32))
(declare-fun a () (_ BitVec 32))
(assert
 (let ((?x35 (bvmul (bvadd a b) x)))
(let ((?x32 (bvmul b x)))
(let ((?x31 (bvmul a x)))
(let ((?x33 (bvadd ?x31 ?x32)))
(and (distinct ?x33 ?x35) true))))))
(check-sat)
