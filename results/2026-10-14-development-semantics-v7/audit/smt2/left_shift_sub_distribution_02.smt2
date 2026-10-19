(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x68 (bvshl y (_ bv2 32))))
(let ((?x64 (bvshl x (_ bv2 32))))
(let ((?x71 (bvsub ?x64 ?x68)))
(let ((?x24 (bvsub x y)))
(let ((?x70 (bvshl ?x24 (_ bv2 32))))
(and (distinct ?x70 ?x71) true)))))))
(check-sat)
