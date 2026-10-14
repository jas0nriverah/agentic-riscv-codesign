(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x236 (bvshl y (_ bv21 32))))
(let ((?x232 (bvshl x (_ bv21 32))))
(let ((?x239 (bvsub ?x232 ?x236)))
(let ((?x24 (bvsub x y)))
(let ((?x238 (bvshl ?x24 (_ bv21 32))))
(and (distinct ?x238 ?x239) true)))))))
(check-sat)
