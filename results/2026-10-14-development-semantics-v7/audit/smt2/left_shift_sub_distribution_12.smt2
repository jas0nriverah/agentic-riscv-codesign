(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x156 (bvshl y (_ bv12 32))))
(let ((?x152 (bvshl x (_ bv12 32))))
(let ((?x159 (bvsub ?x152 ?x156)))
(let ((?x24 (bvsub x y)))
(let ((?x158 (bvshl ?x24 (_ bv12 32))))
(and (distinct ?x158 ?x159) true)))))))
(check-sat)
