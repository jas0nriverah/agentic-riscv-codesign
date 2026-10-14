(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x147 (bvshl y (_ bv11 32))))
(let ((?x143 (bvshl x (_ bv11 32))))
(let ((?x150 (bvsub ?x143 ?x147)))
(let ((?x24 (bvsub x y)))
(let ((?x149 (bvshl ?x24 (_ bv11 32))))
(and (distinct ?x149 ?x150) true)))))))
(check-sat)
