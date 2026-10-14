(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x200 (bvshl y (_ bv17 32))))
(let ((?x196 (bvshl x (_ bv17 32))))
(let ((?x203 (bvsub ?x196 ?x200)))
(let ((?x24 (bvsub x y)))
(let ((?x202 (bvshl ?x24 (_ bv17 32))))
(and (distinct ?x202 ?x203) true)))))))
(check-sat)
