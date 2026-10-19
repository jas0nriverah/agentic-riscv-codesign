(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x68 (bvshl y (_ bv2 32))))
(let ((?x64 (bvshl x (_ bv2 32))))
(let ((?x69 (bvadd ?x64 ?x68)))
(let ((?x19 (bvadd x y)))
(let ((?x67 (bvshl ?x19 (_ bv2 32))))
(and (distinct ?x67 ?x69) true)))))))
(check-sat)
